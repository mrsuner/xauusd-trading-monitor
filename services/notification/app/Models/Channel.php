<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

class Channel extends Model
{
    use HasUuids;

    protected $fillable = [
        'type', 'enabled', 'verified', 'revision', 'enabled_from',
        'encrypted_target', 'target_fingerprint', 'target_hint',
        'link_code_hash', 'link_expires_at', 'linked_at', 'last_error_code',
    ];

    protected function casts(): array
    {
        return [
            'enabled' => 'boolean',
            'verified' => 'boolean',
            'revision' => 'integer',
            'enabled_from' => 'immutable_datetime',
            'link_expires_at' => 'immutable_datetime',
            'linked_at' => 'immutable_datetime',
        ];
    }
}
