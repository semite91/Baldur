namespace Baldur.Warning;

/// <summary>Win32 mouse and keyboard message identifiers used by the filter.</summary>
public static class Wm
{
    public const int MouseMove = 0x0200;
    public const int LButtonDown = 0x0201;
    public const int LButtonUp = 0x0202;
    public const int RButtonDown = 0x0204;
    public const int RButtonUp = 0x0205;
    public const int MButtonDown = 0x0207;
    public const int MButtonUp = 0x0208;
    public const int MouseWheel = 0x020A;
    public const int XButtonDown = 0x020B;
    public const int XButtonUp = 0x020C;
    public const int KeyDown = 0x0100;
    public const int KeyUp = 0x0101;
    public const int SysKeyDown = 0x0104;
}

/// <summary>Pure swallow decision: gated messages die only while blocking.
/// Keyboard-range messages can never match: the hook installed is mouse-only.</summary>
public static class MouseMessageFilter
{
    public static bool ShouldSwallow(int message, bool blocking)
    {
        if (!blocking)
        {
            return false;
        }
        return message is Wm.MouseMove
            or Wm.LButtonDown or Wm.LButtonUp
            or Wm.RButtonDown or Wm.RButtonUp
            or Wm.MButtonDown or Wm.MButtonUp
            or Wm.MouseWheel
            or Wm.XButtonDown or Wm.XButtonUp;
    }
}
