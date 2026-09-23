<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class DigestPreferenceTopic extends Model
{
    public $incrementing = false;

    public $timestamps = false;

    protected $fillable = ['topic'];
}
