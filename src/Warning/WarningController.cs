namespace Baldur.Warning;

/// <summary>Test seam between the controller and any real window.</summary>
public interface IWarningView
{
    void Show();
    void Hide();
}

/// <summary>Routes engine events to the warning view, once per episode.
/// Call Handle on the UI thread: engine callbacks arrive on background
/// threads, so the W4 glue marshals via the Dispatcher before calling here.
/// Keeping the controller dispatcher-free is what keeps it unit-testable.</summary>
public sealed class WarningController(IWarningView view)
{
    private bool _shown;

    public void Handle(EngineEvent e)
    {
        if (e.Name == "bad_posture")
        {
            if (!_shown)
            {
                view.Show();
                _shown = true;
            }
        }
        else if (e.Name == "recovered")
        {
            if (_shown)
            {
                view.Hide();
                _shown = false;
            }
        }
    }
}
