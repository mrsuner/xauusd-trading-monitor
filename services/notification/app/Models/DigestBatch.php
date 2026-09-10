<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\BelongsToMany;

class DigestBatch extends Model
{
    use HasUuids;

    protected $fillable = [
        'subscriber_id', 'channel_id', 'window_start', 'preference_revision',
        'channel_revision', 'content_language', 'status', 'attempt_count',
        'not_before', 'deadline_at', 'last_attempt_at', 'sent_at',
        'provider_message_id', 'error_code',
    ];

    protected function casts(): array
    {
        return [
            'window_start' => 'immutable_datetime', 'not_before' => 'immutable_datetime',
            'deadline_at' => 'immutable_datetime', 'last_attempt_at' => 'immutable_datetime',
            'sent_at' => 'immutable_datetime', 'preference_revision' => 'integer',
            'channel_revision' => 'integer', 'attempt_count' => 'integer',
        ];
    }

    public function subscriber(): BelongsTo
    {
        return $this->belongsTo(Subscriber::class);
    }

    public function channel(): BelongsTo
    {
        return $this->belongsTo(Channel::class);
    }

    public function editions(): BelongsToMany
    {
        return $this->belongsToMany(DigestEdition::class, 'digest_batch_editions', 'batch_id', 'edition_id');
    }
}
