<?php

namespace App\Models;

use App\Enums\DeliveryStatus;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;

class Delivery extends Model
{
    use HasUuids;

    protected $fillable = [
        'subscriber_id', 'channel_id', 'upstream_event_id', 'public_event_id',
        'channel_type', 'priority', 'subscriber_revision', 'channel_revision', 'status',
        'attempt_count', 'not_before', 'dispatch_requested_at',
        'dispatch_confirmed_at', 'last_attempt_at', 'expires_at', 'sent_at',
        'provider_message_id', 'error_code',
    ];

    protected function casts(): array
    {
        return [
            'status' => DeliveryStatus::class,
            'attempt_count' => 'integer',
            'not_before' => 'immutable_datetime',
            'dispatch_requested_at' => 'immutable_datetime',
            'dispatch_confirmed_at' => 'immutable_datetime',
            'last_attempt_at' => 'immutable_datetime',
            'expires_at' => 'immutable_datetime',
            'sent_at' => 'immutable_datetime',
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
}
