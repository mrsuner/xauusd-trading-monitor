<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class DigestEditionEvent extends Model
{
    public $incrementing = false;

    public $timestamps = false;

    protected $fillable = ['public_event_id', 'upstream_event_id', 'position', 'input_payload'];

    protected $primaryKey = null;

    protected function casts(): array
    {
        return ['input_payload' => 'array'];
    }
}
