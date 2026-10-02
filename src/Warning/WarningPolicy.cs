namespace Baldur.Warning;

/// <summary>Close rules for the warning window. Recovery and ESC dismiss
/// through the dismissed path; a user close attempt does not.</summary>
public static class WarningPolicy
{
    public static bool CanClose(bool closable, bool dismissed) => closable || dismissed;

    public static bool ShouldFlash(bool flashEnabled, bool visible, bool rendered) =>
        flashEnabled && visible && rendered;
}
