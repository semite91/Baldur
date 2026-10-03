namespace Baldur.Warning;

/// <summary>Composes engine, view, controller and mouse block into one
/// lifecycle: routes events, trips the watchdog, restarts once, quits clean.
/// Constructed with an already-configured blocker (pass-through in tests).</summary>
public sealed class AppHost : IDisposable
{
    private readonly EngineHost _engine;
    private readonly WarningController _controller;
    private readonly IWarningView _view;
    private readonly MouseBlocker _blocker;
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
            OnEngineGone("heartbeat silence past 10 seconds");
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
        try
        {
            _deadNotified = false;
            HandleEvent(e);
        }
        catch (Exception)
        {
            OnEngineGone("event handling failed");
        }
    }

    private void HandleEvent(EngineEvent e)
    {
        _controller.Handle(e);
        if (e.Name == "bad_posture")
        {
            _blocker.Start();
        }
        else if (e.Name == "recovered")
        {
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
                OnEngineGone("engine restart failed");
            }
            return;
        }
        _view.ShowError("Engine stopped. Posture watch is paused.");
        _blocker.Stop();
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
        _view.ShowError($"Engine gone ({reason}). Posture watch is paused.");
        _blocker.Stop();
    }
}
