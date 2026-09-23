<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class DigestEdition extends Model
{
    use HasUuids;

    protected $fillable = [
        'topic', 'window_start', 'window_end', 'cutoff_at', 'deadline_at', 'status',
        'input_hash', 'input_count', 'coverage_truncated', 'prompt_version',
        'model_provider', 'model_name', 'generation_attempt_count', 'error_code',
        'model_prompt_tokens', 'model_completion_tokens', 'model_latency_ms', 'model_request_ids',
        'published_at', 'invalidated_at', 'invalidation_kind', 'invalidation_reason',
    ];

    protected function casts(): array
    {
        return [
            'window_start' => 'immutable_datetime', 'window_end' => 'immutable_datetime',
            'cutoff_at' => 'immutable_datetime', 'deadline_at' => 'immutable_datetime',
            'published_at' => 'immutable_datetime', 'invalidated_at' => 'immutable_datetime',
            'coverage_truncated' => 'boolean', 'input_count' => 'integer',
            'generation_attempt_count' => 'integer',
            'model_prompt_tokens' => 'integer', 'model_completion_tokens' => 'integer',
            'model_latency_ms' => 'integer', 'model_request_ids' => 'array',
        ];
    }

    public function translations(): HasMany
    {
        return $this->hasMany(DigestTranslation::class, 'edition_id');
    }

    public function events(): HasMany
    {
        return $this->hasMany(DigestEditionEvent::class, 'edition_id')->orderBy('position');
    }
}
