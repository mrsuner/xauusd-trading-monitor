<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class TagSubscription extends Model
{
    public $incrementing = false;

    public $timestamps = false;

    protected $fillable = ['key'];
}
