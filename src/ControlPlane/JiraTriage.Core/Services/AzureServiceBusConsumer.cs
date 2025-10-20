using System.Text;
using System.Text.Json;
using Azure.Identity;
using Azure.Messaging.ServiceBus;

namespace JiraTriage.Core.Services;

public class AzureServiceBusConsumer : IAsyncDisposable
{
    private readonly ServiceBusClient _client;
    private readonly Dictionary<string, ServiceBusProcessor> _processors;
    private readonly SemaphoreSlim _lock = new(1, 1);
    private bool _disposed;

    public AzureServiceBusConsumer(string serviceBusNamespace, bool useLocalEmulator = false)
    {
        if (useLocalEmulator)
        {
            var connectionString = Environment.GetEnvironmentVariable("SERVICEBUS_CONNECTION_STRING") 
                ?? throw new InvalidOperationException("SERVICEBUS_CONNECTION_STRING not set for local emulator");
            _client = new ServiceBusClient(connectionString);
        }
        else
        {
            var credential = new DefaultAzureCredential();
            _client = new ServiceBusClient(serviceBusNamespace, credential);
        }
        
        _processors = new Dictionary<string, ServiceBusProcessor>();
        Console.WriteLine($"[ServiceBus] Initialized consumer for namespace: {serviceBusNamespace}");
    }

    public static AzureServiceBusConsumer CreateFromEnvironment()
    {
        var useLocal = Environment.GetEnvironmentVariable("USE_LOCAL_SERVICEBUS")?.ToLower() == "true";
        var serviceBusNamespace = Environment.GetEnvironmentVariable("SERVICEBUS_NAMESPACE") 
            ?? "jiratriage.servicebus.windows.net";
        
        return new AzureServiceBusConsumer(serviceBusNamespace, useLocal);
    }

    public async Task RegisterHandlerAsync<T>(
        string queueName,
        Func<T, CancellationToken, Task> messageHandler,
        int maxConcurrentCalls = 1) where T : class
    {
        await _lock.WaitAsync();
        try
        {
            if (_processors.ContainsKey(queueName))
            {
                throw new InvalidOperationException($"Handler already registered for queue: {queueName}");
            }

            var processor = _client.CreateProcessor(queueName, new ServiceBusProcessorOptions
            {
                MaxConcurrentCalls = maxConcurrentCalls,
                AutoCompleteMessages = false,
                MaxAutoLockRenewalDuration = TimeSpan.FromMinutes(5)
            });

            processor.ProcessMessageAsync += async args =>
            {
                try
                {
                    var messageBody = Encoding.UTF8.GetString(args.Message.Body.ToArray());
                    var message = JsonSerializer.Deserialize<T>(messageBody);
                    
                    if (message != null)
                    {
                        Console.WriteLine($"[ServiceBus] Processing message from {queueName} (MessageId: {args.Message.MessageId})");
                        
                        await messageHandler(message, args.CancellationToken);
                        
                        await args.CompleteMessageAsync(args.Message);
                        Console.WriteLine($"[ServiceBus] Completed message {args.Message.MessageId}");
                    }
                    else
                    {
                        Console.WriteLine($"[ServiceBus] Failed to deserialize message {args.Message.MessageId}, dead-lettering");
                        await args.DeadLetterMessageAsync(args.Message, "DeserializationFailed");
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[ServiceBus] Error processing message {args.Message.MessageId}: {ex.Message}");
                    
                    if (args.Message.DeliveryCount >= 3)
                    {
                        Console.WriteLine($"[ServiceBus] Max retries exceeded, dead-lettering message {args.Message.MessageId}");
                        await args.DeadLetterMessageAsync(args.Message, "MaxRetriesExceeded", ex.Message);
                    }
                    else
                    {
                        await args.AbandonMessageAsync(args.Message);
                    }
                }
            };

            processor.ProcessErrorAsync += args =>
            {
                Console.WriteLine($"[ServiceBus] Error in processor for {queueName}: {args.Exception.Message}");
                return Task.CompletedTask;
            };

            await processor.StartProcessingAsync();
            _processors[queueName] = processor;
            
            Console.WriteLine($"[ServiceBus] Started processor for queue: {queueName}");
        }
        finally
        {
            _lock.Release();
        }
    }

    public async Task StopProcessingAsync(string queueName)
    {
        await _lock.WaitAsync();
        try
        {
            if (_processors.TryGetValue(queueName, out var processor))
            {
                await processor.StopProcessingAsync();
                Console.WriteLine($"[ServiceBus] Stopped processor for queue: {queueName}");
            }
        }
        finally
        {
            _lock.Release();
        }
    }

    public async ValueTask DisposeAsync()
    {
        if (_disposed)
        {
            return;
        }

        _disposed = true;

        await _lock.WaitAsync();
        try
        {
            foreach (var (queueName, processor) in _processors)
            {
                try
                {
                    await processor.StopProcessingAsync();
                    await processor.DisposeAsync();
                    Console.WriteLine($"[ServiceBus] Disposed processor for queue: {queueName}");
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"[ServiceBus] Error disposing processor for {queueName}: {ex.Message}");
                }
            }
            _processors.Clear();
        }
        finally
        {
            _lock.Release();
        }

        await _client.DisposeAsync();
        _lock.Dispose();
        
        Console.WriteLine("[ServiceBus] Consumer disposed");
    }
}
