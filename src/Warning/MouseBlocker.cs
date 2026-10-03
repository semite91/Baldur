using System.Windows;

namespace Baldur.Warning;

/// <summary>WH_MOUSE_LL swallow plus ClipCursor combo. The hook is installed
/// in pass-through mode by tests; only the blocking flag (from popup state
/// and config) arms swallowing. Keyboard is untouched: no keyboard hook
/// exists, so keystrokes physically cannot flow through this proc.
/// Threading contract: call Start and Stop on the same UI thread. Low-level
/// hooks fire only on threads running a message loop, so installing from a
/// background thread would silently never swallow; the W4 glue owns this.</summary>
public sealed class MouseBlocker : IDisposable
{
    private readonly bool _blockingEnabled;
    private NativeMethods.HookProc? _proc;
    private IntPtr _hookId = IntPtr.Zero;
    private bool _disposed;

    public MouseBlocker(bool blockingEnabled)
    {
        _blockingEnabled = blockingEnabled;
    }

    public bool IsHookInstalled => _hookId != IntPtr.Zero;

    public static Int32Rect PrimaryScreenClipRect() => new(0, 0,
        Math.Max(1, (int)SystemParameters.PrimaryScreenWidth),
        Math.Max(1, (int)SystemParameters.PrimaryScreenHeight));

    public void Start()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        if (IsHookInstalled)
        {
            return;
        }
        _proc = HookCallback;
        _hookId = NativeMethods.SetWindowsHookEx(
            NativeMethods.WhMouseLl, _proc, NativeMethods.GetModuleHandle(null), 0);
        if (_hookId == IntPtr.Zero)
        {
            _proc = null;
            throw new System.ComponentModel.Win32Exception();
        }
        if (_blockingEnabled)
        {
            var rect = PrimaryScreenClipRect();
            var bounds = new NativeMethods.Rect
            {
                Left = rect.X,
                Top = rect.Y,
                Right = rect.X + rect.Width,
                Bottom = rect.Y + rect.Height,
            };
            NativeMethods.ClipCursor(ref bounds);
        }
    }

    public void Stop()
    {
        if (!IsHookInstalled)
        {
            return;
        }
        NativeMethods.UnhookWindowsHookEx(_hookId);
        _hookId = IntPtr.Zero;
        _proc = null;
        NativeMethods.ClipCursor(IntPtr.Zero);
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        Stop();
    }

    private IntPtr HookCallback(int nCode, IntPtr wParam, IntPtr lParam)
    {
        if (nCode >= 0 && MouseMessageFilter.ShouldSwallow((int)wParam, _blockingEnabled))
        {
            return (IntPtr)1;
        }
        return NativeMethods.CallNextHookEx(IntPtr.Zero, nCode, wParam, lParam);
    }
}
