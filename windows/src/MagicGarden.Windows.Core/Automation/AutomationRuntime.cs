using MagicGarden.Windows.Core.Protocol;
using MagicGarden.Windows.Core.State;

namespace MagicGarden.Windows.Core.Automation;

public sealed class AutomationRuntime
{
    private readonly RoomClient _client;
    public AutomationController Controller {get;}=new();
    public StateConfirmation Confirmation {get;}
    public AutomationRuntime(RoomClient client)
    {
        _client=client; Confirmation=new(client.State);
        client.MessageApplied += _ => OnAuthoritativeStateChanged();
        client.ProtocolWarning += x => Controller.Log?.Invoke(x);
    }
    private void OnAuthoritativeStateChanged()
    {
        Controller.AuthoritativeReady=_client.IsAuthoritativeReady;
        // Planners replace intents from the newest authoritative snapshot.
        // No fixed-delay scheduler is permitted here.
    }
}
