using System.Collections.Concurrent;
using System.Text.Json;

namespace JiraTriage.Core.Services;

public class InMemoryQueuePublisher : IQueuePublisher
{
    private static readonly ConcurrentDictionary<string, ConcurrentQueue<string>> Queues = new();

    public Task PublishAsync<T>(string queueName, T message) where T : class
    {
        var queue = Queues.GetOrAdd(queueName, _ => new ConcurrentQueue<string>());
        var serialized = JsonSerializer.Serialize(message);
        queue.Enqueue(serialized);
        Console.WriteLine($"[Queue] Published to {queueName}: {typeof(T).Name}");
        return Task.CompletedTask;
    }

    public static bool TryDequeue(string queueName, out string? message)
    {
        if (Queues.TryGetValue(queueName, out var queue))
        {
            return queue.TryDequeue(out message);
        }
        message = null;
        return false;
    }

    public static int GetQueueCount(string queueName)
    {
        return Queues.TryGetValue(queueName, out var queue) ? queue.Count : 0;
    }
}
