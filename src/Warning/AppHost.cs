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

    public AppHost(EngineHost engine, IWarningView view, MouseBlocker blocker)
    {
        _engine = engine;
        _view = view;
        _blocker = blocker;
        _controller = new WarningController(view);
        _ui = (view as System.Windows.Threading.DispatcherObject)?.Dispatcher;
        _view.DismissRequested += OnEscapeDismiss;
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
        Marshal(() =>
        {
            try
            {
                _deadNotified = false;
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
            _view.ShowError("Engine reported an error. Posture watch is paused.");
            _blocker.Stop();
        }
    }

    private void OnEngineExited()
    {
        Log("engine process exited");
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
            _view.ShowError("Engine stopped. Posture watch is paused.");
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
