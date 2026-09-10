<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Concerns\HasUuids;
use Illuminate\Database\Eloquent\Model;

class DigestTranslation extends Model
{
    use HasUuids;

    protected $fillable = ['edition_id', 'language', 'title', 'overview', 'developments', 'source_content_hash'];

    protected function casts(): array
    {
        return ['developments' => 'array'];
    }
}
