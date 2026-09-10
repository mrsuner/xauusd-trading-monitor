<?php

namespace App\Console\Commands;

use App\Services\Telegram\TelegramApi;
use App\Services\Telegram\TelegramUpdateProcessor;
use Illuminate\Console\Command;

class PollTelegramUpdates extends Command
{
    protected $signature = 'telegram:poll {--once : Poll once and exit}';

    protected $description = 'Consume Telegram channel-link and stop commands';

    public function handle(TelegramApi $telegram, TelegramUpdateProcessor $processor): int
    {
        $webhook = $telegram->webhookInfo();
        if (trim((string) ($webhook['url'] ?? '')) !== '') {
            $this->error('Telegram webhook is configured; refusing to start long polling.');

            return self::FAILURE;
        }

        do {
            $updates = $telegram->updates($processor->nextOffset());
            $processor->process($updates);
        } while (! $this->option('once'));

        return self::SUCCESS;
    }
}
