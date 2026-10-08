using System.Windows.Forms;

namespace Baldur.Warning;

/// <summary>Tray presence for the background app. Construction and disposal
/// are headless-safe; showing the icon needs a running shell (manual gate).</summary>
public sealed class TrayController : IDisposable
{
    private readonly NotifyIcon _icon;
    private readonly ContextMenuStrip _menu;
    private bool _disposed;

    public event Action? QuitRequested;

    public TrayController()
    {
        _icon = new NotifyIcon
        {
            Text = "Baldur",
            Visible = false,
        };
        _menu = new ContextMenuStrip();
        var quit = new ToolStripMenuItem("Quit");
        quit.Click += (_, _) => QuitRequested?.Invoke();
        _menu.Items.Add(quit);
        _icon.ContextMenuStrip = _menu;
    }

    public ToolStripMenuItem QuitItem => (ToolStripMenuItem)_icon.ContextMenuStrip!.Items[0];

    public void Show()
    {
        ObjectDisposedException.ThrowIf(_disposed, this);
        _icon.Visible = true;
    }

    public void Dispose()
    {
        if (_disposed)
        {
            return;
        }
        _disposed = true;
        _icon.Visible = false;
        _icon.Dispose();
        _menu.Dispose();
    }
}
