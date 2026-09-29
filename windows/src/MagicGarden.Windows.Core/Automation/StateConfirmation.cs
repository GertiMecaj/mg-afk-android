using MagicGarden.Windows.Core.State;

namespace MagicGarden.Windows.Core.Automation;

public sealed class StateConfirmation(AuthoritativeGameState state)
{
    public async Task<bool> AfterAsync(long beforeRevision,Func<AuthoritativeGameState,bool> predicate,TimeSpan timeout,CancellationToken ct)
    {
        if(state.Revision>beforeRevision && predicate(state))return true;
        var until=DateTime.UtcNow+timeout;
        while(DateTime.UtcNow<until)
        {
            await Task.Delay(50,ct);
            if(state.Revision>beforeRevision && predicate(state))return true;
        }
        return false;
    }
}
