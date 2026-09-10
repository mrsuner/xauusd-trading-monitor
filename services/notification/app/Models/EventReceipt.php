<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class EventReceipt extends Model
{
    protected $primaryKey = 'upstream_event_id';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = ['upstream_event_id', 'public_event_id', 'received_at', 'processed_at', 'expires_at'];

    protected function casts(): array
    {
        return [
            'received_at' => 'immutable_datetime',
            'processed_at' => 'immutable_datetime',
            'expires_at' => 'immutable_datetime',
        ];
    }
}
