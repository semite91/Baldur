using Baldur.Warning;

namespace Warning.Tests;

public sealed class WatchdogPolicyTests
{
    [Theory]
    [InlineData(9.9, false)]
    [InlineData(10.0, false)]
    [InlineData(10.1, true)]
    public void SilenceBoundary(double secondsSilent, bool expectedDead)
    {
        var now = DateTimeOffset.UtcNow;
        Assert.Equal(expectedDead, WatchdogPolicy.IsDead(now.AddSeconds(-secondsSilent), now));
    }
}
