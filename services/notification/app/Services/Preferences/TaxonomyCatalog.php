<?php

namespace App\Services\Preferences;

use Illuminate\Support\Facades\Cache;
use Illuminate\Support\Facades\DB;
use RuntimeException;

class TaxonomyCatalog
{
    /** @return array{categories: list<string>, tags: list<string>} */
    public function keys(): array
    {
        return Cache::remember('subscription-taxonomy:v1', 300, function (): array {
            $categories = DB::table($this->table('public_subscription_categories'))
                ->orderBy('key')->pluck('key')->map(fn (mixed $key): string => (string) $key)->all();
            $tags = DB::table($this->table('public_subscription_tags'))
                ->orderBy('key')->pluck('key')->map(fn (mixed $key): string => (string) $key)->all();

            if ($categories === [] || $tags === []) {
                throw new RuntimeException('Subscription taxonomy is unavailable.');
            }

            return ['categories' => $categories, 'tags' => $tags];
        });
    }

    private function table(string $table): string
    {
        return DB::getDriverName() === 'pgsql' ? 'public.'.$table : $table;
    }
}
