using System.ComponentModel;
using System.Windows;
using System.Windows.Input;

namespace Baldur.Warning;

/// <summary>Small centered camera-unavailable dialog. Never the fullscreen
/// warning modal: normal chrome, message plus Close (always) and Continue
/// (mid-run only, hidden otherwise). Close and X quit the app through the
/// boot quit path; ESC does the same per the key map. Resume hides the
/// dialog with Hide (never Close, so no quit fires).</summary>
public partial class CameraDialog : Window
{
    private bool _closingRaised;

    public CameraDialog(bool withContinue)
    {
        InitializeComponent();
        if (!withContinue)
        {
            ContinueButton.Visibility = Visibility.Collapsed;
        }
    }

    public event Action? CloseRequested;

    public event Action? ContinueRequested;

    /// <summary>Mid-run Continue: re-probe the camera (host decides).</summary>
    public void RequestContinue() => ContinueRequested?.Invoke();

    private void OnCloseClick(object sender, RoutedEventArgs e) => Close();

    private void OnContinueClick(object sender, RoutedEventArgs e) => RequestContinue();

    private void OnKeyDown(object sender, System.Windows.Input.KeyEventArgs e)
    {
        if (e.Key is Key.Escape)
        {
            Close();
        }
    }

    protected override void OnClosing(CancelEventArgs e)
    {
        base.OnClosing(e);
        if (_closingRaised)
        {
            return;
        }
        _closingRaised = true;
        CloseRequested?.Invoke();
    }
}
