using MagicGarden.Windows.Core.Protocol;
namespace MagicGarden.Windows.Core.Automation;

public sealed class AutomationRuntime
{
    private readonly RoomClient _client;
    private ProjectsPlanner? _planner;
    private Func<ProjectSettings>? _settings;
    private Func<bool>? _dryRun;
    public AutomationController Controller {get;}=new();
    public StateConfirmation Confirmation {get;}
    public AutomationRuntime(RoomClient client)
    {
        _client=client; Confirmation=new(client.State);
        client.MessageApplied += _ => OnAuthoritativeStateChanged();
        client.ProtocolWarning += Controller.Report;
    }
    public void Configure(ProjectsPlanner planner,Func<ProjectSettings> settings,Func<bool>? dryRun=null)
    { _planner=planner;_settings=settings;_dryRun=dryRun;Replan(); }
    public void Replan()
    {
        Controller.AuthoritativeReady=_client.IsAuthoritativeReady;
        if(!Controller.AuthoritativeReady||_planner is null||_settings is null){Controller.ReplaceIntents([]);return;}
        var intents=_planner.Build(_settings()).ToArray();
        if(_dryRun?.Invoke()==true) intents=intents.Select(Simulate).ToArray();
        Controller.ReplaceIntents(intents);
    }
    private AutomationIntent Simulate(AutomationIntent i)=>new(i.Project,i.Priority,i.Resources,_=>{
        Controller.Report($"SIMULATE {i.Project}: {string.Join(", ",i.Resources.Select(x=>$"{x.Kind}:{x.Id}"))}");
        return Task.FromResult(false);
    });
    private void OnAuthoritativeStateChanged()=>Replan();
}
