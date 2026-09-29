using System.Threading;

namespace MagicGarden.Windows.Core.Protocol;

public sealed class CommandSequencer
{
    private long _next = 1;
    public void Seed(long executedCommandSequence) => Interlocked.Exchange(ref _next, executedCommandSequence + 1);
    public long Next() => Interlocked.Increment(ref _next) - 1;
    public void Reset() => Interlocked.Exchange(ref _next, 1);
}
