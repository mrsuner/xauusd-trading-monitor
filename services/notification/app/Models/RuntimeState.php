<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class RuntimeState extends Model
{
    protected $table = 'runtime_state';

    protected $primaryKey = 'key';

    public $incrementing = false;

    protected $keyType = 'string';

    protected $fillable = ['key', 'value'];

    protected function casts(): array
    {
        return ['value' => 'array'];
    }
}
