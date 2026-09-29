namespace MagicGarden.Windows.Core.Automation;

public sealed record ProjectSettings(
    string PlayerId,
    string? DatabaseId,
    IReadOnlySet<string> PlantSpecies,
    IReadOnlySet<string> HarvestSpecies,
    IReadOnlySet<string> ShopItems,
    IReadOnlySet<string> EggTypes,
    IReadOnlyDictionary<string,string> PetFoodByPetId,
    IReadOnlyDictionary<string,string> WeatherTeams,
    string DefaultTeamId,
    string? SellBoostTeamId,
    string? HatchMutationTeamId,
    int InventoryCapacity,
    int EmptyPlotReserve=13,
    double EmergencyHungerPercent=10.0);
