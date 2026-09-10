<?php

namespace App\Models;

use App\Enums\Severity;
use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;
use Illuminate\Database\Eloquent\Relations\HasMany;

class Subscriber extends Model
{
    use HasUuids;

    protected $fillable = [
        'account_user_id',
        'master_enabled',
        'match_all_categories',
        'min_severity',
        'content_language',
        'revision',
        'effective_from',
    ];

    protected function casts(): array
    {
        return [
            'master_enabled' => 'boolean',
            'match_all_categories' => 'boolean',
            'min_severity' => Severity::class,
            'revision' => 'integer',
            'effective_from' => 'immutable_datetime',
        ];
    }

    public function categories(): HasMany
    {
        return $this->hasMany(CategorySubscription::class);
    }

    public function tags(): HasMany
    {
        return $this->hasMany(TagSubscription::class);
    }

    public function channels(): HasMany
    {
        return $this->hasMany(Channel::class);
    }
}
