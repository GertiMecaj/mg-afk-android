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

        // D: emergency feed. Existing produce -> mature garden food -> plant emergency food -> buy seed.
        foreach(var pet in StateViews.OwnedPets(s,cfg.PlayerId,cfg.DatabaseId))
        {
            var id=Str(pet,"id") ?? Str(pet,"itemId"); if(id is null || !cfg.PetFoodByPetId.TryGetValue(id,out var food)) continue;
            var hunger=Num(pet,"hungerPercent") ?? Num(pet,"hunger"); if(hunger is null || hunger>cfg.EmergencyHungerPercent) continue;

            var produce=items.OfType<JsonObject>()
                .Where(x=>Str(x,"species")==food && (Str(x,"itemType")=="Produce"||Str(x,"type")=="Produce"))
                .OrderBy(x=>MutationPenalty(x)).ThenBy(x=>Num(x,"value")??Num(x,"sellValue")??double.MaxValue).FirstOrDefault();
            if(produce is not null && (Str(produce,"id")??Str(produce,"itemId")) is string cropId)
            {
                yield return Intent("D-feed",ProjectPriority.DEmergencyFeed,[new(ResourceKind.Pet,id),new(ResourceKind.Inventory,cropId)],
                    Confirmed(a=>a.FeedPetAsync(id,cropId),x=>!HasInventoryId(x,cfg,cropId)));
                continue;
            }

            var foodCrop=StateViews.Crops(s,cfg.PlayerId,cfg.DatabaseId).FirstOrDefault(x=>Str(x.crop,"species")==food);
            if(foodCrop.crop is not null)
            {
                if(Mature(foodCrop.crop))
                    yield return Intent("D-harvest-food",ProjectPriority.DEmergencyFeed,[new(ResourceKind.GardenPlot,foodCrop.tileObjectIdx.ToString()),new(ResourceKind.Inventory,"capacity")],
                        Confirmed(a=>a.HarvestCropAsync(foodCrop.tileObjectIdx,foodCrop.growSlotIdx),x=>!CropExists(x,cfg,foodCrop.tileObjectIdx,foodCrop.growSlotIdx,food)));
                else if(NeedsWater(foodCrop.crop))
                    yield return Intent("D-water-food",ProjectPriority.DEmergencyFeed,[new(ResourceKind.GardenPlot,foodCrop.tileObjectIdx.ToString())],
                        Confirmed(a=>a.WaterPlantAsync(foodCrop.tileObjectIdx),x=>!NeedsWaterAt(x,cfg,foodCrop.tileObjectIdx,foodCrop.growSlotIdx)));
                continue;
            }

            var emergencySlot=EmptyPlots(s,cfg).FirstOrDefault(-1);
            if(emergencySlot>=0 && HasSeed(items,food))
            {
                yield return Intent("D-plant-food",ProjectPriority.DEmergencyFeed,[new(ResourceKind.GardenPlot,emergencySlot.ToString())],
                    Confirmed(a=>a.PlantSeedAsync(emergencySlot,food),x=>!EmptyPlots(x,cfg).Contains(emergencySlot)));
                continue;
            }
            if(emergencySlot>=0 && TryShopItem(s,food,out var foodShop,out var foodType,out var foodField))
                yield return Intent("D-buy-food",ProjectPriority.DEmergencyFeed,[new(ResourceKind.Shop,foodShop)],
                    Confirmed(a=>a.PurchaseShopItemAsync(foodShop,foodType,foodField,food),x=>HasSeed(x.InventoryItems(cfg.PlayerId,cfg.DatabaseId),food)));
        }

        // F: weather team, otherwise Default. Temporary B/E teams restore by recalculating this at completion.
        var weather=s.Weather();
        var target=!string.IsNullOrWhiteSpace(weather)&&cfg.WeatherTeams.TryGetValue(weather!,out var wt)?wt:cfg.DefaultTeamId;
        if(!string.IsNullOrWhiteSpace(target) && !TeamIsActive(s,cfg,target))
            yield return Intent("F",ProjectPriority.FWeatherTeam,[new(ResourceKind.PetTeam,"active")],
                Confirmed(a=>a.ApplyPetTeamAsync(target),x=>TeamIsActive(x,cfg,target)));

        // B: sell only at actual full inventory; switch to sell boost first when configured.
        if(full)
            yield return Intent("B-sell",ProjectPriority.BFullInventorySell,[new(ResourceKind.Sell,"all"),new(ResourceKind.PetTeam,"active")],
                async ()=>{
                    if(!IsFull(cfg))return false;
                    if(!string.IsNullOrWhiteSpace(cfg.SellBoostTeamId) && !TeamIsActive(client.State,cfg,cfg.SellBoostTeamId!) && !await Confirmed(a=>a.ApplyPetTeamAsync(cfg.SellBoostTeamId!),x=>TeamIsActive(x,cfg,cfg.SellBoostTeamId!))())return false;
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

        // E: full egg lifecycle. Ignores the 13-empty-plot reserve.
        foreach(var egg in cfg.EggTypes)
        {
            var planted=FindPlantedEgg(s,cfg,egg);
            if(planted is { } pe)
            {
                if(EggReady(pe.node))
                    yield return Intent("E-hatch",ProjectPriority.EHatchReady,[new(ResourceKind.GardenPlot,pe.slot.ToString()),new(ResourceKind.PetTeam,"active")],
                        async()=>{
                            if(!string.IsNullOrWhiteSpace(cfg.HatchMutationTeamId) && !TeamIsActive(client.State,cfg,cfg.HatchMutationTeamId!) && !await Confirmed(a=>a.ApplyPetTeamAsync(cfg.HatchMutationTeamId!),x=>TeamIsActive(x,cfg,cfg.HatchMutationTeamId!))()) return false;
                            var ok=await Confirmed(a=>a.HatchEggAsync(pe.slot),x=>FindPlantedEgg(x,cfg,egg) is null)();
                            await RestoreTeam(cfg); return ok;
                        });
                continue;
            }

            var ownedEgg=FindInventoryEgg(items,egg);
            var eggSlot=EmptyPlots(s,cfg).FirstOrDefault(-1);
            if(ownedEgg is not null && eggSlot>=0)
            {
                yield return Intent("E-plant",ProjectPriority.EPlantEgg,[new(ResourceKind.GardenPlot,eggSlot.ToString()),new(ResourceKind.Inventory,egg)],
                    Confirmed(a=>a.GrowEggAsync(eggSlot,egg),x=>FindPlantedEgg(x,cfg,egg) is not null));
                continue;
            }
            if(ownedEgg is null && TryShopItem(s,egg,out var eggShop,out var eggType,out var eggField))
                yield return Intent("E-buy",ProjectPriority.EPlantEgg,[new(ResourceKind.Shop,eggShop)],
                    Confirmed(a=>a.PurchaseShopItemAsync(eggShop,eggType,eggField,egg),x=>FindInventoryEgg(x.InventoryItems(cfg.PlayerId,cfg.DatabaseId),egg) is not null));
        }

        // A: preserve 13 empty plots; consume owned seed first, otherwise buy only for usable capacity.
        var empty=EmptyPlots(s,cfg);
        if(empty.Count>cfg.EmptyPlotReserve)
        {
            var usable=empty.Take(empty.Count-cfg.EmptyPlotReserve).ToArray();
            foreach(var species in cfg.PlantSpecies)
            {
                if(usable.Length==0) break;
                if(HasSeed(items,species))
                {
                    var slot=usable[0];
                    yield return Intent("A-plant",ProjectPriority.APlant,[new(ResourceKind.GardenPlot,slot.ToString())],
                        Confirmed(a=>a.PlantSeedAsync(slot,species),x=>!EmptyPlots(x,cfg).Contains(slot)));
                }
                else if(TryShopItem(s,species,out var seedShop,out var seedType,out var seedField))
                    yield return Intent("A-buy-seed",ProjectPriority.APlant,[new(ResourceKind.Shop,seedShop)],
                        Confirmed(a=>a.PurchaseShopItemAsync(seedShop,seedType,seedField,species),x=>HasSeed(x.InventoryItems(cfg.PlayerId,cfg.DatabaseId),species)));
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
    private async Task RestoreTeam(ProjectSettings c){var w=client.State.Weather();var t=!string.IsNullOrWhiteSpace(w)&&c.WeatherTeams.TryGetValue(w!,out var x)?x:c.DefaultTeamId;if(!string.IsNullOrWhiteSpace(t)&&!TeamIsActive(client.State,c,t))await Confirmed(a=>a.ApplyPetTeamAsync(t),s=>TeamIsActive(s,c,t))();}
    private static bool TeamIsActive(AuthoritativeGameState s,ProjectSettings c,string teamId){
        var d=s.UserData(c.PlayerId,c.DatabaseId);if(d is null)return false;
        foreach(var k in new[]{"activePetTeamId","selectedPetTeamId","petTeamId"})if(d[k]?.GetValue<string>()==teamId)return true;
        if(d["petTeams"] is JsonArray teams)foreach(var t in teams.OfType<JsonObject>())if((Str(t,"id")==teamId||Str(t,"teamId")==teamId)&&(t["isActive"]?.GetValue<bool>()==true||t["active"]?.GetValue<bool>()==true))return true;
        return false;
    }
    private static bool Mature(JsonObject c){if(c["isMature"]?.GetValue<bool>()==true)return true;var e=Num(c,"endTime");return e is not null&&e<=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();}
    private static bool HasEgg(AuthoritativeGameState s,ProjectSettings c,string egg)=>s.InventoryItems(c.PlayerId,c.DatabaseId).OfType<JsonObject>().Any(x=>Str(x,"eggId")==egg||Str(x,"species")==egg);
    private static List<int> EmptyPlots(AuthoritativeGameState s,ProjectSettings c){var g=s.Garden(c.PlayerId,c.DatabaseId) as JsonObject;var n=g?["tileObjects"];var r=new List<int>();
        if(n is JsonObject o){foreach(var kv in o)if(int.TryParse(kv.Key,out var i)&&kv.Value is null)r.Add(i);return r;}
        if(n is JsonArray a){for(int i=0;i<a.Count;i++)if(a[i] is null)r.Add(i);}return r;}
    private static bool ShopContains(AuthoritativeGameState s,string id)=>s.Shops().ToJsonString().Contains(id,StringComparison.Ordinal);
    private static bool HasSeed(JsonArray items,string species)=>items.OfType<JsonObject>().Any(x=>Str(x,"species")==species&&(Str(x,"itemType")=="Seed"||Str(x,"type")=="Seed"));
    private static JsonObject? FindInventoryEgg(JsonArray items,string egg)=>items.OfType<JsonObject>().FirstOrDefault(x=>Str(x,"eggId")==egg&&(Str(x,"itemType")=="Egg"||Str(x,"type")=="Egg"||x["eggId"] is not null));
    private static bool HasInventoryId(AuthoritativeGameState s,ProjectSettings c,string id)=>s.InventoryItems(c.PlayerId,c.DatabaseId).OfType<JsonObject>().Any(x=>Str(x,"id")==id||Str(x,"itemId")==id);
    private static int MutationPenalty(JsonObject x){var t=x.ToJsonString();return t.Contains("Gold",StringComparison.OrdinalIgnoreCase)||t.Contains("Rainbow",StringComparison.OrdinalIgnoreCase)?1:0;}
    private static bool NeedsWater(JsonObject c)=>c["isWatered"]?.GetValue<bool>()==false||c["watered"]?.GetValue<bool>()==false||c["needsWater"]?.GetValue<bool>()==true;
    private static bool NeedsWaterAt(AuthoritativeGameState s,ProjectSettings c,int tile,int grow)=>StateViews.Crops(s,c.PlayerId,c.DatabaseId).Any(x=>x.tileObjectIdx==tile&&x.growSlotIdx==grow&&NeedsWater(x.crop));
    private static bool CropExists(AuthoritativeGameState s,ProjectSettings c,int tile,int grow,string species)=>StateViews.Crops(s,c.PlayerId,c.DatabaseId).Any(x=>x.tileObjectIdx==tile&&x.growSlotIdx==grow&&Str(x.crop,"species")==species);
    private static bool EggReady(JsonObject e){if(e["isReady"]?.GetValue<bool>()==true||e["isMature"]?.GetValue<bool>()==true)return true;var end=Num(e,"endTime")??Num(e,"hatchTime");return end is not null&&end<=DateTimeOffset.UtcNow.ToUnixTimeMilliseconds();}
    private static (int slot,JsonObject node)? FindPlantedEgg(AuthoritativeGameState s,ProjectSettings c,string egg){
        foreach(var (i,o) in StateViews.GardenTiles(s,c.PlayerId,c.DatabaseId)){var n=FindObject(o,x=>Str(x,"eggId")==egg);if(n is not null)return(i,n);}return null;
    }
    private static JsonObject? FindObject(JsonNode? n,Func<JsonObject,bool> p){if(n is JsonObject o){if(p(o))return o;foreach(var kv in o){var z=FindObject(kv.Value,p);if(z is not null)return z;}}else if(n is JsonArray a)foreach(var v in a){var z=FindObject(v,p);if(z is not null)return z;}return null;}
    private static bool TryShopItem(AuthoritativeGameState s,string id,out string shop,out string itemType,out string idField){
        shop=itemType=idField="";if(s.Shops() is not JsonObject shops)return false;
        foreach(var kv in shops){if(kv.Value is not JsonObject so||so["inventory"] is not JsonArray inv)continue;foreach(var e in inv.OfType<JsonObject>()){
            var initial=Num(e,"initialStock");if(initial is not null&&initial<=0)continue;
            var item=e["item"] as JsonObject??e;foreach(var pair in new[]{("species","Seed"),("toolId","Tool"),("eggId","Egg"),("decorId","Decor")})
                if(Str(item,pair.Item1)==id){shop=kv.Key;idField=pair.Item1;itemType=pair.Item2;return true;}
        }}return false;
    }
    private static string? Str(JsonObject? o,string k)=>o?[k] is JsonValue v&&v.TryGetValue<string>(out var x)?x:null;
    private static double? Num(JsonObject o,string k)=>o[k] is JsonValue v&&v.TryGetValue<double>(out var x)?x:null;
}
