using System.Text.Json.Nodes;
using MagicGarden.Windows.Core.Protocol;
using MagicGarden.Windows.Core.State;

namespace MagicGarden.Windows.Core.Automation;

public sealed class ProjectsPlanner(RoomClient client, StateConfirmation confirm)
{
    public IEnumerable<AutomationIntent> Build(ProjectSettings cfg)
    {
        if(!client.IsAuthoritativeReady) yield break;
        var s=client.State;
        var items=s.InventoryItems(cfg.PlayerId,cfg.DatabaseId);
        var full=cfg.InventoryCapacity>0 && items.Count>=cfg.InventoryCapacity;

        // D: emergency feed always outranks normal farming and may consume reserved plots.
        foreach(var pet in StateViews.OwnedPets(s,cfg.PlayerId,cfg.DatabaseId))
        {
            var id=Str(pet,"id") ?? Str(pet,"itemId"); if(id is null || !cfg.PetFoodByPetId.TryGetValue(id,out var food)) continue;
            var hunger=Num(pet,"hungerPercent") ?? Num(pet,"hunger"); if(hunger is null || hunger>cfg.EmergencyHungerPercent) continue;
            var crop=items.OfType<JsonObject>().FirstOrDefault(x=>Str(x,"species")==food && (Str(x,"itemType")=="Produce"||Str(x,"type")=="Produce"));
            if(crop is not null && (Str(crop,"id")??Str(crop,"itemId")) is string cropId)
                yield return Intent("D",ProjectPriority.DEmergencyFeed,[new(ResourceKind.Pet,id),new(ResourceKind.Inventory,cropId)],
                    Confirmed(a=>a.FeedPetAsync(id,cropId),x=>!x.InventoryItems(cfg.PlayerId,cfg.DatabaseId).Any(n=>(n as JsonObject)?["id"]?.GetValue<string>()==cropId)));
        }

        // F: weather team, otherwise Default. Temporary B/E teams restore by recalculating this at completion.
        var weather=s.Weather();
        var target=!string.IsNullOrWhiteSpace(weather)&&cfg.WeatherTeams.TryGetValue(weather!,out var wt)?wt:cfg.DefaultTeamId;
        if(!string.IsNullOrWhiteSpace(target))
            yield return Intent("F",ProjectPriority.FWeatherTeam,[new(ResourceKind.PetTeam,"active")],
                Confirmed(a=>a.ApplyPetTeamAsync(target),_=>true));

        // B: sell only at actual full inventory; switch to sell boost first when configured.
        if(full)
            yield return Intent("B-sell",ProjectPriority.BFullInventorySell,[new(ResourceKind.Sell,"all"),new(ResourceKind.PetTeam,"active")],
                async ()=>{
                    if(!IsFull(cfg))return false;
                    if(!string.IsNullOrWhiteSpace(cfg.SellBoostTeamId) && !await Confirmed(a=>a.ApplyPetTeamAsync(cfg.SellBoostTeamId!),_=>true)())return false;
                    if(!IsFull(cfg)) { await RestoreTeam(cfg); return false; }
                    var sold=await Confirmed(a=>a.SellAllCropsAsync(),x=>x.InventoryItems(cfg.PlayerId,cfg.DatabaseId).Count<cfg.InventoryCapacity)();
                    await RestoreTeam(cfg); return sold;
                });

        // B: harvest configured mature crops; multi-grow-slot index is preserved.
        foreach(var (tile,grow,crop) in StateViews.Crops(s,cfg.PlayerId,cfg.DatabaseId))
        {
            var species=Str(crop,"species"); if(species is null || !cfg.HarvestSpecies.Contains(species) || !Mature(crop))continue;
            yield return Intent("B-harvest",ProjectPriority.BHarvest,[new(ResourceKind.GardenPlot,tile.ToString()),new(ResourceKind.Inventory,"capacity")],
                Confirmed(a=>a.HarvestCropAsync(tile,grow),_=>true));
        }

        // E: enabled eggs ignore the 13-plot reserve. Existing owned/growing egg prevents duplicate buy intent.
        foreach(var egg in cfg.EggTypes)
        {
            if(HasEgg(s,cfg,egg))continue;
            yield return Intent("E-buy",ProjectPriority.EPlantEgg,[new(ResourceKind.Shop,"egg")],
                Confirmed(a=>a.PurchaseShopItemAsync("egg","Egg","eggId",egg),x=>HasEgg(x,cfg,egg)));
        }

        // A: ordinary planting preserves 13 empty plots and consumes owned seed before purchase.
        var empty=EmptyPlots(s,cfg);
        if(empty.Count>cfg.EmptyPlotReserve)
        {
            var usable=empty.Take(empty.Count-cfg.EmptyPlotReserve).ToArray();
            foreach(var species in cfg.PlantSpecies)
            {
                var seed=items.OfType<JsonObject>().FirstOrDefault(x=>Str(x,"species")==species && (Str(x,"itemType")=="Seed"||Str(x,"type")=="Seed"));
                if(seed is null)continue;
                foreach(var slot in usable.Take(1))
                    yield return Intent("A",ProjectPriority.APlant,[new(ResourceKind.GardenPlot,slot.ToString())],
                        Confirmed(a=>a.PlantSeedAsync(slot,species),x=>!EmptyPlots(x,cfg).Contains(slot)));
            }
        }

        // C: only emits purchase work for enabled ids that the authoritative shop snapshot exposes.
        foreach(var id in cfg.ShopItems)
            if(ShopContains(s,id))
                yield return Intent("C",ProjectPriority.CShop,[new(ResourceKind.Shop,id)],
                    Confirmed(a=>a.PurchaseShopItemAsync("tool","Tool","toolId",id),x=>x.InventoryItems(cfg.PlayerId,cfg.DatabaseId).Any(n=>n is JsonObject o && (Str(o,"id")==id || Str(o,"itemId")==id || Str(o,"toolId")==id || Str(o,"decorId")==id))));
    }

    private AutomationIntent Intent(string p,int pri,IReadOnlyList<ResourceKey> r,Func<Task<bool>> run)=>new(p,pri,r,_=>run());
    private Func<Task<bool>> Confirmed(Func<GameActions,Task> send,Func<AuthoritativeGameState,bool> ok)=>async()=>{
        var before=client.State.Revision; await send(client.Actions); return await confirm.AfterAsync(before,ok,TimeSpan.FromSeconds(8),CancellationToken.None);
    };
    private bool IsFull(ProjectSettings c)=>c.InventoryCapacity>0&&client.State.InventoryItems(c.PlayerId,c.DatabaseId).Count>=c.InventoryCapacity;
    private async Task RestoreTeam(ProjectSettings c){var w=client.State.Weather();var t=!string.IsNullOrWhiteSpace(w)&&c.WeatherTeams.TryGetValue(w!,out var x)?x:c.DefaultTeamId;if(!string.IsNullOrWhiteSpace(t))await client.Actions.ApplyPetTeamAsync(t);}
    private static bool Mature(JsonObject c){if(c["isMature"]?.GetValue<bool>()==true)return true;var e=Num(c,"endTime");return e is not null&&e<=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();}
    private static bool HasEgg(AuthoritativeGameState s,ProjectSettings c,string egg)=>s.InventoryItems(c.PlayerId,c.DatabaseId).OfType<JsonObject>().Any(x=>Str(x,"eggId")==egg||Str(x,"species")==egg);
    private static List<int> EmptyPlots(AuthoritativeGameState s,ProjectSettings c){var g=s.Garden(c.PlayerId,c.DatabaseId) as JsonObject;var a=g?["tileObjects"] as JsonArray;var r=new List<int>();if(a is null)return r;for(int i=0;i<a.Count;i++)if(a[i] is null)r.Add(i);return r;}
    private static bool ShopContains(AuthoritativeGameState s,string id)=>s.Shops().ToJsonString().Contains(id,StringComparison.Ordinal);
    private static string? Str(JsonObject? o,string k)=>o?[k] is JsonValue v&&v.TryGetValue<string>(out var x)?x:null;
    private static double? Num(JsonObject o,string k)=>o[k] is JsonValue v&&v.TryGetValue<double>(out var x)?x:null;
}
