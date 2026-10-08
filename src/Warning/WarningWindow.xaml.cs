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
    private bool _wasActive = true;
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
        _flashTimer.Tick += (_, _) =>
        {
            if (WarningPolicy.ShouldFlash(_config.FlashEnabled, IsVisible, _rendered))
            {
                ToggleFlash();
            }
            EnsureKeyboardFocus();
            if (IsVisible && IsActive != _wasActive)
            {
                _wasActive = IsActive;
                LogFocus("tick");
            }
        };
        IsVisibleChanged += (_, _) =>
        {
            // The window must own keyboard focus or dismiss keys land in
            // whatever app had it (preview window, terminal, VS Code) and
            // the mouse block stops the user from clicking back. Focus is
            // re-asserted on every tick while visible because background
            // processes cannot rely on a single Activate winning.
            if (IsVisible)
            {
                Activate();
                _flashTimer.Start();
                LogFocus("shown");
            }
            else
            {
                _flashTimer.Stop();
                _wasActive = true;
            }
        };
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
        if (IsVisible)
        {
            _flashTimer.Start();
        }
    }

    /// <summary>Pull keyboard focus back while visible; no-op when hidden
    /// or already active. Returns true when activation was attempted.
    /// Public for unit tests.</summary>
    public bool EnsureKeyboardFocus()
    {
        if (!IsVisible || IsActive)
        {
            return false;
        }
        Activate();
        Focus();
        return true;
    }

    /// <summary>E2E ground truth: reports whether this window owns
    /// activation and keyboard focus. The engine child's pipes hide all
    /// of this, so without the log a dead key is indistinguishable from
    /// a dead handler. Console-less launches drop these lines silently.</summary>
    private void LogFocus(string stage)
    {
        var focused = System.Windows.Input.Keyboard.FocusedElement;
        Console.Error.WriteLine(
            $"baldur[focus] {stage} visible={IsVisible} active={IsActive} " +
            $"focused={(focused is null ? "none" : focused.GetType().Name)}");
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
        DismissOnKey(e.Key);
    }

    /// <summary>Keyboard dismissal: ENTER hides the warning (host teardown,
    /// app keeps running); ESC quits the app completely (boot wiring runs
    /// the tray-quit path). Returns true when the key was handled. The
    /// window is never closed here so ENTER keeps it re-showable.</summary>
    public bool DismissOnKey(System.Windows.Input.Key key)
    {
        if (key is System.Windows.Input.Key.Escape)
        {
            // Never Close() here: the boot quit path owns shutdown order
            // (window, engine, tray, process).
            _dismissed = true;
            QuitRequested?.Invoke();
            return true;
        } 
        if (key is System.Windows.Input.Key.Enter)
        {
            // Never Close() here: a closed WPF window cannot re-Show, and
            // the mouse block lives in the host. The host answers with the
            // shared teardown (hide plus unblock plus episode reset).
            _dismissed = true;
            DismissRequested?.Invoke();
            return true;
        }
        return false;
    }

    public event Action? DismissRequested;

    public event Action? QuitRequested;

    private void ToggleFlash()
    {
        _lit = !_lit;
        HeaderText.Foreground = _lit ? _plainBrush : _alertBrush;
    }
}
