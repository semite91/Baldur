namespace Baldur.Warning;

/// <summary>Composes engine, view, controller and mouse block into one
/// lifecycle: routes events, trips the watchdog, restarts once, quits clean.
/// Constructed with an already-configured blocker (pass-through in tests).
/// Threading: engine callbacks arrive on background threads, so all view
/// plus blocker transitions are marshalled to the view's Dispatcher when
/// the view is a real window. Fake views in tests stay dispatcher-free.</summary>
public sealed class AppHost : IDisposable
{
    private readonly EngineHost _engine;
    private readonly WarningController _controller;
    private readonly IWarningView _view;
    private readonly MouseBlocker _blocker;
    private readonly System.Windows.Threading.Dispatcher? _ui;
    private string _fileName = string.Empty;
    private string _arguments = string.Empty;
    private bool _restartAttempted;
    private bool _quitRequested;
    private bool _disposed;
    private bool _started;
    private bool _deadNotified;
    private bool _sawLife;
    private bool _cameraErrorSeen;
    private bool _cameraNotified;
    private bool _dialogOpen;
    private bool _resuming;
    private readonly string? _probeFile;
    private readonly string? _probeArgs;
    private readonly Func<string, string, int> _probeRunner;

    private static readonly HashSet<string> CameraCodes = new(StringComparer.Ordinal)
    {
        "CAMERA_UNAVAILABLE", "FRAME_READ_FAILED",
    };

    public event Action<bool>? CameraDialogRequested;

    public event Action? CameraDialogDismissed;

    /// <summary>Life signs that dismiss a camera dialog: any event proving
    /// the engine watches again. Unit-tested directly.</summary>
    public static bool IsSignOfLife(string name) =>
        name is "heartbeat" or "bad_posture" or "recovered";

    public AppHost(EngineHost engine, IWarningView view, MouseBlocker blocker,
        string? probeFile = null, string? probeArgs = null,
        Func<string, string, int>? probeRunner = null)
    {
        _engine = engine;
        _view = view;
        _blocker = blocker;
        _controller = new WarningController(view);
        _ui = (view as System.Windows.Threading.DispatcherObject)?.Dispatcher;
        _view.DismissRequested += OnEscapeDismiss;
        _probeFile = probeFile;
        _probeArgs = probeArgs;
        _probeRunner = probeRunner ?? RunProbeProcess;
    }

    public void Start(string fileName, string arguments)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (_started)
        {
            throw new InvalidOperationException("Host already started.");
        }
        _fileName = fileName;
        _arguments = arguments;
        _engine.EventReceived += OnEngineEvent;
        _engine.Exited += OnEngineExited;
        try
        {
            StartEngine(fileName, arguments);
        }
        catch
        {
            _engine.EventReceived -= OnEngineEvent;
            _engine.Exited -= OnEngineExited;
            throw;
        }
        _started = true;
    }

    public int EngineProcessId => _engine.ProcessId;

    /// <summary>Continue after a camera dialog: probe first (when a probe
    /// is configured), relaunch the engine only when a camera answers.
    /// Safe to press repeatedly: at most one probe/relaunch is ever in
    /// flight. Returns false when there is nothing to resume.</summary>
    public bool TryResume()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (!_started || _quitRequested || _resuming)
        {
            return false;
        }
        if (_engine.ProcessId != 0)
        {
            return true;
        }
        _resuming = true;
        _restartAttempted = true;
        _deadNotified = false;
        _cameraNotified = false;
        if (_probeFile is null)
        {
            return ResumeNow();
        }
        var file = _probeFile;
        var args = _probeArgs ?? string.Empty;
        var runner = _probeRunner;
        Log("continue pressed -> probing camera");
        System.Threading.Tasks.Task.Run(() =>
        {
            int code;
            try
            {
                code = runner(file, args);
            }
            catch
            {
                code = 2;
            }
            if (code == 0)
            {
                ResumeNow();
            }
            else
            {
                Log("probe found no camera; staying parked");
                _resuming = false;
            }
        });
        return true;
    }

    private bool ResumeNow()
    {
        try
        {
            StartEngine(_fileName, _arguments);
        }
        catch (Exception)
        {
            _resuming = false;
            return false;
        }
        return true;
    }

    private static int RunProbeProcess(string file, string args)
    {
        try
        {
            using var process = new System.Diagnostics.Process
            {
                StartInfo = new System.Diagnostics.ProcessStartInfo
                {
                    FileName = file,
                    Arguments = args,
                    UseShellExecute = false,
                    RedirectStandardOutput = true,
                    RedirectStandardError = true,
                    CreateNoWindow = true,
                },
            };
            process.Start();
            if (!process.WaitForExit(20000))
            {
                try
                {
                    process.Kill(entireProcessTree: true);
                }
                catch (InvalidOperationException)
                {
                }
                return 2;
            }
            return process.ExitCode;
        }
        catch
        {
            return 2;
        }
    }

    public void CheckWatchdog(DateTimeOffset now)
    {
        if (!_quitRequested && WatchdogPolicy.IsDead(_engine.LastReceivedAtUtc, now))
        {
            Marshal(() => OnEngineGone("heartbeat silence past 10 seconds"));
        }
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        _quitRequested = true;
        _view.DismissRequested -= OnEscapeDismiss;
        _engine.EventReceived -= OnEngineEvent;
        _engine.Exited -= OnEngineExited;
        _blocker.Dispose();
        _engine.Dispose();
    }

    private void StartEngine(string fileName, string arguments)
    {
        _engine.Start(fileName, arguments);
    }

    private void OnEngineEvent(EngineEvent e)
    {
        Log($"rx {e.Name}");
        _resuming = false;
        Marshal(() =>
        {
            try
            {
                _deadNotified = false;
                NoteSignOfLife(e);
                HandleEvent(e);
            }
            catch (Exception)
            {
                OnEngineGone("event handling failed");
            }
        });
    }

    private void HandleEvent(EngineEvent e)
    {
        _controller.Handle(e);
        if (e.Name == "bad_posture")
        {
            Log("bad_posture -> show + block");
            _blocker.Start();
        }
        else if (e.Name == "recovered")
        {
            Log("recovered -> hide + unblock");
            _blocker.Stop();
        }
        else if (e.Name == "error")
        {
            _blocker.Stop();
            if (e.Code is not null && CameraCodes.Contains(e.Code))
            {
                _cameraErrorSeen = true;
                RequestCameraDialog();
            }
            else
            {
                _view.ShowError("Engine reported an error. Posture watch is paused.");
            }
        }
    }

    private void NoteSignOfLife(EngineEvent e)
    {
        if (!IsSignOfLife(e.Name))
        {
            return;
        }
        _sawLife = true;
        if (_dialogOpen)
        {
            _dialogOpen = false;
            Log("watching resumed -> hide camera dialog");
            CameraDialogDismissed?.Invoke();
        }
    }

    private void RequestCameraDialog()
    {
        if (_disposed || _cameraNotified)
        {
            return;
        }
        _cameraNotified = true;
        _dialogOpen = true;
        Log($"camera dialog requested (canContinue={_sawLife})");
        CameraDialogRequested?.Invoke(_sawLife);
    }

    private void OnEngineExited()
    {
        Log("engine process exited");
        _resuming = false;
        if (_quitRequested)
        {
            return;
        }
        if (!_restartAttempted)
        {
            _restartAttempted = true;
            try
            {
                StartEngine(_fileName, _arguments);
            }
            catch (Exception)
            {
                Marshal(() => OnEngineGone("engine restart failed"));
            }
            return;
        }
        Marshal(() =>
        {
            if (_cameraErrorSeen)
            {
                RequestCameraDialog();
            }
            else
            {
                _view.ShowError("Engine stopped. Posture watch is paused.");
            }
            _blocker.Stop();
        });
    }

    private void OnEngineGone(string reason)
    {
        if (_disposed)
        {
            return;
        }
        if (_deadNotified)
        {
            return;
        }
        _deadNotified = true;
        Log($"engine gone ({reason})");
        _view.ShowError($"Engine gone ({reason}). Posture watch is paused.");
        _blocker.Stop();
    }

    /// <summary>E2E observability: the engine child's stdout/stderr are
    /// piped and drained, so without this the dotnet terminal shows nothing
    /// of what the host sees. stderr is never parsed by anyone.</summary>
    private static void Log(string message) =>
        Console.Error.WriteLine($"baldur[host] {message}");

    /// <summary>Shared dismiss teardown (same as recovered): hide the view,
    /// release the mouse, and re-arm the episode so the next bad_posture
    /// shows again. The window itself is never closed, so it stays
    /// re-showable for the life of the host.</summary>
    private void OnEscapeDismiss()
    {
        Log("dismiss -> hide + unblock");
        Marshal(() =>
        {
            _controller.Reset();
            _view.Hide();
            _blocker.Stop();
        });
    }

    private void Marshal(System.Action action)
    {
        var ui = _ui;
        if (ui is null || ui.CheckAccess())
        {
            action();
            return;
        }
        ui.Invoke(action);
    }
}
