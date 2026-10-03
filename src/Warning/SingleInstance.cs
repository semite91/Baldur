namespace Baldur.Warning;

/// <summary>Single-instance guard: the second launch exits without side effects.</summary>
public static class SingleInstance
{
    public static bool TryAcquire(string name, out IDisposable lease)
    {
        try
        {
            var mutex = new Mutex(initiallyOwned: true, name, out var createdNew);
            if (!createdNew)
            {
                mutex.Dispose();
                lease = null!;
                return false;
            }
            lease = mutex;
            return true;
        }
        catch (AbandonedMutexException ex)
        {
            // Previous owner died without releasing; take over. Not covered by
            // automated tests: abandonment delivery is not controllable from
            // managed test code. Verify manually by killing a holder process
            // and relaunching.
            lease = ex.Mutex!;
            return true;
        }
    }
}
