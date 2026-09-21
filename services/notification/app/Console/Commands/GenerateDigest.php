<?php

namespace App\Console\Commands;

use App\Services\Digests\DigestEditionFreezer;
use App\Services\Digests\DigestGenerator;
use App\Services\Digests\DigestInputRepository;
use Carbon\CarbonImmutable;
use Illuminate\Console\Command;
use Throwable;

class GenerateDigest extends Command
{
    protected $signature = 'digest:generate
        {--date= : UTC window date in YYYY-MM-DD format; defaults to yesterday}
        {--topic=* : One or more configured topics; defaults to all topics}
        {--dry-run : Inspect selected events without writing or calling the model}';

    protected $description = 'Inspect or synchronously generate shared daily digest editions';

    public function __construct(
        private readonly DigestInputRepository $inputs,
        private readonly DigestEditionFreezer $freezer,
        private readonly DigestGenerator $generator,
    ) {
        parent::__construct();
    }

    public function handle(): int
    {
        try {
            $windowStart = $this->windowStart();
            $topics = $this->topics();
        } catch (Throwable $exception) {
            $this->error($exception->getMessage());

            return self::INVALID;
        }
        $windowEnd = $windowStart->addDay();
        $rows = [];
        $failed = false;

        foreach ($topics as $topic) {
            if ((bool) $this->option('dry-run')) {
                $selection = $this->inputs->select(
                    $topic,
                    $windowStart,
                    $windowEnd,
                    (int) config('notification.digest.input_limit', 20),
                );
                $rows[] = [
                    $topic,
                    count($selection['events']),
                    $selection['truncated'] ? 'yes' : 'no',
                    implode(',', array_map(fn ($event): string => $event->id, $selection['events'])),
                ];

                continue;
            }

            $edition = $this->freezer->freeze($topic, $windowStart, $windowEnd, dispatchGeneration: false);
            if ($edition->status === 'frozen') {
                $retryAfter = $this->generator->generate($edition->id);
                $failed = $failed || $retryAfter !== null;
            }
            $edition->refresh();
            $rows[] = [
                $topic,
                $edition->status,
                $edition->input_count,
                $edition->model_prompt_tokens + $edition->model_completion_tokens,
                $edition->model_latency_ms,
                $edition->error_code ?? '—',
            ];
            $failed = $failed || $edition->status === 'failed';
        }

        $this->newLine();
        $this->info('Digest window: '.$windowStart->toDateString().' UTC');
        if ((bool) $this->option('dry-run')) {
            $this->table(['Topic', 'Events', 'Truncated', 'Event IDs'], $rows);
        } else {
            $this->table(['Topic', 'Status', 'Events', 'Tokens', 'Latency ms', 'Error'], $rows);
        }

        return $failed ? self::FAILURE : self::SUCCESS;
    }

    private function windowStart(): CarbonImmutable
    {
        $date = trim((string) ($this->option('date') ?: CarbonImmutable::now('UTC')->subDay()->toDateString()));
        if (preg_match('/^\d{4}-\d{2}-\d{2}$/', $date) !== 1) {
            throw new \InvalidArgumentException('The --date value must use YYYY-MM-DD.');
        }
        try {
            $parsed = CarbonImmutable::createFromFormat('!Y-m-d', $date, 'UTC');
        } catch (Throwable) {
            throw new \InvalidArgumentException('The --date value must use YYYY-MM-DD.');
        }
        if ($parsed === false || $parsed->toDateString() !== $date) {
            throw new \InvalidArgumentException('The --date value must use YYYY-MM-DD.');
        }

        return $parsed;
    }

    /** @return list<string> */
    private function topics(): array
    {
        $available = array_values(array_map('strval', config('notification.digest.topics', [])));
        $requested = array_values(array_unique(array_filter(array_map('strval', (array) $this->option('topic')))));
        if ($requested === []) {
            return $available;
        }
        $unknown = array_values(array_diff($requested, $available));
        if ($unknown !== []) {
            throw new \InvalidArgumentException('Unknown digest topic(s): '.implode(', ', $unknown));
        }

        return $requested;
    }
}
