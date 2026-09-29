namespace MagicGarden.Windows.Core.Automation;

public enum ResourceKind { GardenPlot, Inventory, PetTeam, Shop, Storage, Pet, Sell }
public sealed record ResourceKey(ResourceKind Kind,string Id);
public sealed record AutomationIntent(string Project,int Priority,IReadOnlyList<ResourceKey> Resources,Func<CancellationToken,Task<bool>> Execute);

public sealed class ResourceLocks
{
    private readonly object _gate=new();
    private readonly HashSet<ResourceKey> _held=[];
    public bool TryAcquire(IEnumerable<ResourceKey> resources,out IDisposable? lease)
    {
        var r=resources.Distinct().ToArray();
        lock(_gate)
        {
            if(r.Any(_held.Contains)){lease=null;return false;}
            foreach(var x in r)_held.Add(x);
        }
        lease=new Lease(this,r); return true;
    }
    private void Release(ResourceKey[] r){lock(_gate)foreach(var x in r)_held.Remove(x);}
    private sealed class Lease(ResourceLocks owner,ResourceKey[] r):IDisposable
    { private int _done; public void Dispose(){if(Interlocked.Exchange(ref _done,1)==0)owner.Release(r);} }
}

public sealed class AutomationController
{
    private readonly ResourceLocks _locks=new();
    private readonly SemaphoreSlim _wake=new(0,1);
    private readonly object _gate=new();
    private List<AutomationIntent> _intents=[];
    public bool AuthoritativeReady {get;set;}
    public event Action<string>? Log;

    public void ReplaceIntents(IEnumerable<AutomationIntent> intents)
    {
        lock(_gate)_intents=intents.OrderByDescending(x=>x.Priority).ToList();
        if(_wake.CurrentCount==0)_wake.Release();
    }

    public async Task RunAsync(CancellationToken ct)
    {
        while(!ct.IsCancellationRequested)
        {
            await _wake.WaitAsync(ct);
            if(!AuthoritativeReady)continue;
            while(true)
            {
                AutomationIntent[] work; lock(_gate)work=_intents.ToArray();
                var ran=false;
                foreach(var i in work)
                {
                    if(!_locks.TryAcquire(i.Resources,out var lease))continue;
                    using(lease)
                    {
                        try { ran=await i.Execute(ct); if(ran){Log?.Invoke(i.Project);break;} }
                        catch(OperationCanceledException) when(ct.IsCancellationRequested){throw;}
                        catch(Exception e){Log?.Invoke($"{i.Project} failed: {e.Message}");}
                    }
                }
                if(!ran)break;
            }
        }
    }
}
