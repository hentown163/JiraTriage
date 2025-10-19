using JiraTriage.Core.Services;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSingleton<IQueuePublisher, InMemoryQueuePublisher>();

builder.WebHost.ConfigureKestrel(options =>
{
    options.ListenAnyIP(5001);
});

var app = builder.Build();

app.MapControllers();

app.MapGet("/", () => new 
{ 
    service = "JIRA Triage Webhook - Control Plane",
    status = "operational",
    architecture = "Hybrid Polyglot - .NET Control Layer"
});

app.Run();
