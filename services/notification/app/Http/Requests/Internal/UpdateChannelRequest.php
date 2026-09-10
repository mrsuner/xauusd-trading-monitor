<?php

namespace App\Http\Requests\Internal;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Validator;

class UpdateChannelRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return ['enabled' => ['required', 'boolean']];
    }

    public function after(): array
    {
        return [
            function (Validator $validator): void {
                $unknown = array_diff(array_keys($this->all()), ['enabled']);
                if ($unknown !== []) {
                    $validator->errors()->add('request', 'Unknown fields: '.implode(', ', $unknown).'.');
                }
            },
        ];
    }
}
