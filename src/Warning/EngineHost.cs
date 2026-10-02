using System.Diagnostics;

namespace Baldur.Warning;

/// <summary>
/// Owns the Recognition child process: launches it with piped stdout,
/// raises one event per frozen JSON line, drains stderr so a chatty child
/// can never deadlock the reader, and kills the whole tree on dispose.
/// </summary>
public sealed class EngineHost : IDisposable
{
    private Process? _process;
    private int _malformedCount;
    private bool _disposed;

    public event Action<EngineEvent>? EventReceived;

    public event Action? Exited;

    public int MalformedCount => _malformedCount;

    public DateTimeOffset LastReceivedAtUtc { get; private set; } = DateTimeOffset.MinValue;

    public int ProcessId => _process?.Id ?? 0;

    public void Start(string fileName, string arguments)
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        ArgumentException.ThrowIfNullOrWhiteSpace(fileName);
        if (_process is not null)
        {
            throw new InvalidOperationException("Engine already started.");
        }
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
        process.Exited += (_, _) => Exited?.Invoke();
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

    public bool WaitForExit(TimeSpan timeout)
    {
        var process = _process;
        if (process is null)
        {
            return false;
        }
        if (!process.WaitForExit((int)timeout.TotalMilliseconds))
        {
            return false;
        }
        process.WaitForExit();
        return true;
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        var process = _process;
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
}
