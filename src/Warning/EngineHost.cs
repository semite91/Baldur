using System.Diagnostics;

namespace Baldur.Warning;

/// <summary>
/// Owns the Recognition child process: launches it with piped stdout,
/// raises one event per frozen JSON line, drains stderr so a chatty child
/// can never deadlock the reader, and kills the whole tree on dispose.
/// Restartable: a dead child is reaped on Exited, so Start works again.
/// All lifecycle transitions hold one lock; event subscribers must never
/// call back into blocking host methods from the handler thread.
/// </summary>
public sealed class EngineHost : IDisposable
{
    private readonly object _gate = new();
    private Process? _process;
    private int _malformedCount;
    private bool _disposed;

    public event Action<EngineEvent>? EventReceived;

    public event Action? Exited;

    public int MalformedCount => _malformedCount;

    public DateTimeOffset LastReceivedAtUtc { get; private set; } = DateTimeOffset.MinValue;

    public int ProcessId
    {
        get
        {
            lock (_gate)
            {
                return _process?.Id ?? 0;
            }
        }
    }

    public void Start(string fileName, string arguments)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);
        var startInfo = new ProcessStartInfo
        {
            FileName = fileName,
            Arguments = arguments,
            UseShellExecute = false,
            RedirectStandardOutput = true,
            RedirectStandardError = true,
            CreateNoWindow = true,
        };
        var process = new Process { StartInfo = startInfo, EnableRaisingEvents = true };
        process.OutputDataReceived += (_, args) =>
        {
            if (args.Data is null)
            {
                return;
            }
            if (EngineEvent.TryParse(args.Data, out var parsed) && parsed is not null)
            {
                LastReceivedAtUtc = parsed.ReceivedAt;
                EventReceived?.Invoke(parsed);
            }
            else
            {
                Interlocked.Increment(ref _malformedCount);
            }
        };
        process.ErrorDataReceived += (_, _) => { };
        process.Exited += (_, _) => OnProcessExited();
        lock (_gate)
        {
            if (_process is not null)
            {
                process.Dispose();
                throw new InvalidOperationException("Engine already started.");
            }
            try
            {
                process.Start();
            }
            catch
            {
                process.Dispose();
                throw;
            }
            process.BeginOutputReadLine();
            process.BeginErrorReadLine();
            _process = process;
        }
    }

    public bool WaitForExit(TimeSpan timeout)
    {
        Process? process;
        lock (_gate)
        {
            process = _process;
        }
        if (process is null)
        {
            return false;
        }
        try
        {
            if (!process.WaitForExit((int)timeout.TotalMilliseconds))
            {
                return false;
            }
            process.WaitForExit();
        }
        catch (InvalidOperationException)
        {
            return true;
        }
        return true;
    }

    public void Dispose()
    {
        Process? process;
        lock (_gate)
        {
            if (_disposed)
            {
                return;
            }
            _disposed = true;
            process = _process;
            _process = null;
        }
        if (process is null)
        {
            return;
        }
        try
        {
            if (!process.HasExited)
            {
                process.Kill(entireProcessTree: true);
            }
        }
        catch (InvalidOperationException)
        {
        }
        try
        {
            process.WaitForExit((int)TimeSpan.FromSeconds(5).TotalMilliseconds);
        }
        catch (InvalidOperationException)
        {
        }
        process.Dispose();
    }

    private void OnProcessExited()
    {
        Process? dead;
        lock (_gate)
        {
            dead = _process;
            _process = null;
        }
        dead?.Dispose();
        Exited?.Invoke();
    }
}
