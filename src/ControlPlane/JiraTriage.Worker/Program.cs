using JiraTriage.Worker.Workers;
using JiraTriage.Core.Services;

var builder = Host.CreateApplicationBuilder(args);
builder.Services.AddHostedService<TicketEnrichmentWorker>();
builder.Services.AddHttpClient();
builder.Services.AddSingleton<IQueuePublisher, InMemoryQueuePublisher>();
builder.Services.AddSingleton<DecisionLogService>();

var host = builder.Build();
host.Run();
