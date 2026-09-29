namespace MagicGarden.Windows.Core.Automation;

public static class ProjectPriority
{
    // Higher wins. Emergency feeding is deliberately above every ordinary farming task.
    public const int DEmergencyFeed=1000;
    public const int EHatchReady=900;
    public const int TemporaryPetOptimization=850;
    public const int FWeatherTeam=800;
    public const int BFullInventorySell=700;
    public const int BHarvest=600;
    public const int EPlantEgg=500;
    public const int APlant=400;
    public const int CShop=300;
}
