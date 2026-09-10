<?php

namespace App\Models;

use Illuminate\Database\Eloquent\Model;

class CategorySubscription extends Model
{
    public $incrementing = false;

    public $timestamps = false;

    protected $fillable = ['key'];
}
