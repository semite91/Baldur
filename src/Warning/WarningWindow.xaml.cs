using System.ComponentModel;
using System.Windows;
using System.Windows.Input;
using System.Windows.Media;
using System.Windows.Threading;

namespace Baldur.Warning;

/// <summary>Fullscreen always-on-top warning. Shown on bad_posture only.</summary>
public partial class WarningWindow : Window, IWarningView
{
    private readonly WarningConfig _config;
    private readonly DispatcherTimer _flashTimer;
    private readonly System.Windows.Media.Brush _alertBrush = System.Windows.Media.Brushes.Red;
    private readonly System.Windows.Media.Brush _plainBrush = System.Windows.Media.Brushes.White;
    private bool _dismissed;
    private bool _systemClose;
    private bool _rendered;
    private bool _lit;

    public WarningWindow()
        : this(new WarningConfig())
    {
    }

    public WarningWindow(WarningConfig config)
    {
        _config = config;
        InitializeComponent();
        _flashTimer = new DispatcherTimer { Interval = TimeSpan.FromMilliseconds(500) };
        _flashTimer.Tick += (_, _) => ToggleFlash();
        IsVisibleChanged += (_, _) => ApplyFlashPolicy();
        if (System.Windows.Application.Current is not null)
        {
            System.Windows.Application.Current.SessionEnding += (_, _) => _systemClose = true;
        }
    }

    public void DismissForRecovery()
    {
        ForceClose();
    }

    /// <summary>Engine failure display: detail text, no flashing red, always closable.</summary>
    public void ShowErrorDetails(string message)
    {
        _flashTimer.Stop();
        DetailText.Text = message;
        DetailText.Visibility = Visibility.Visible;
    }

    public void ShowError(string message)
    {
        ShowErrorDetails(message);
        if (!IsVisible)
        {
            Show();
        }
    }

    /// <summary>Host-driven shutdown (tray quit, app exit): bypasses the user-close policy.</summary>
    public void ForceClose()
    {
        _dismissed = true;
        Close();
    }

    protected override void OnContentRendered(EventArgs e)
    {
        base.OnContentRendered(e);
        _rendered = true;
        ApplyFlashPolicy();
    }

    private void ApplyFlashPolicy()
    {
        if (WarningPolicy.ShouldFlash(_config.FlashEnabled, IsVisible, _rendered))
        {
            _flashTimer.Start();
        }
        else
        {
            _flashTimer.Stop();
        }
    }

    protected override void OnClosing(CancelEventArgs e)
    {
        _flashTimer.Stop();
        if (!_systemClose && !WarningPolicy.CanClose(_config.IsWarningWindowClosable, _dismissed))
        {
            e.Cancel = true;
        }
        base.OnClosing(e);
    }

    private void OnKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key == System.Windows.Input.Key.Escape)
        {
            _dismissed = true;
            Close();
        }
    }

    private void ToggleFlash()
    {
        _lit = !_lit;
        HeaderText.Foreground = _lit ? _plainBrush : _alertBrush;
    }
}
