namespace Baldur.Warning;

/// <summary>Engine-death tripwire: silence past the threshold means dead.
/// Locked at 10 seconds (two missed 5s heartbeats): fail fast rather than
/// idle through false coverage.</summary>
public static class WatchdogPolicy
{
    public const double SilenceThresholdSeconds = 10.0;

    public static bool IsDead(DateTimeOffset lastBeat, DateTimeOffset now) =>
        (now - lastBeat).TotalSeconds > SilenceThresholdSeconds;
}
