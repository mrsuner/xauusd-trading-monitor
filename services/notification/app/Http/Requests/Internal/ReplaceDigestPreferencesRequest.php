<?php

namespace App\Http\Requests\Internal;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

class ReplaceDigestPreferencesRequest extends FormRequest
{
    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'enabled' => ['required', 'boolean'],
            'topics' => ['present', 'array', 'max:4'],
            'topics.*' => ['string', 'distinct', Rule::in(config('notification.digest.topics', []))],
        ];
    }

    public function after(): array
    {
        return [function (Validator $validator): void {
            $unknown = array_diff(array_keys($this->all()), ['enabled', 'topics']);
            if ($unknown !== []) {
                $validator->errors()->add('request', 'Unknown fields: '.implode(', ', $unknown).'.');
            }
            if ($this->boolean('enabled') && $this->array('topics') === []) {
                $validator->errors()->add('topics', 'Select at least one topic before enabling digests.');
            }
        }];
    }
}
