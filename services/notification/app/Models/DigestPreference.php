<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\BelongsTo;
use Illuminate\Database\Eloquent\Relations\HasMany;

class DigestPreference extends Model
{
    protected $primaryKey = 'subscriber_id';

    protected $keyType = 'string';

    public $incrementing = false;

    protected $fillable = ['subscriber_id', 'enabled', 'revision', 'effective_from'];

    protected function casts(): array
    {
        return ['enabled' => 'boolean', 'revision' => 'integer', 'effective_from' => 'immutable_datetime'];
    }

    public function subscriber(): BelongsTo
    {
        return $this->belongsTo(Subscriber::class);
    }

    public function topics(): HasMany
    {
        return $this->hasMany(DigestPreferenceTopic::class, 'subscriber_id', 'subscriber_id');
    }
}
