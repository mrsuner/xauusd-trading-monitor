<?php

namespace App\Http\Requests\Internal;

use Illuminate\Foundation\Http\FormRequest;
use Illuminate\Validation\Rule;
use Illuminate\Validation\Validator;

class ReplacePreferencesRequest extends FormRequest
{
    private const FIELDS = [
        'master_enabled', 'match_all_categories', 'min_severity',
        'content_language', 'categories', 'tags',
    ];

    public function authorize(): bool
    {
        return true;
    }

    public function rules(): array
    {
        return [
            'master_enabled' => ['required', 'boolean'],
            'match_all_categories' => ['required', 'boolean'],
            'min_severity' => ['required', Rule::in(['S', 'A', 'B', 'C'])],
            'content_language' => ['required', Rule::in(config('notification.supported_languages', []))],
            'categories' => ['present', 'array', 'max:50'],
            'categories.*' => ['string', 'distinct', 'max:128'],
            'tags' => ['present', 'array', 'max:50'],
            'tags.*' => ['string', 'distinct', 'max:128'],
        ];
    }

    public function after(): array
    {
        return [
            function (Validator $validator): void {
                $unknown = array_diff(array_keys($this->all()), self::FIELDS);
                if ($unknown !== []) {
                    $validator->errors()->add('request', 'Unknown fields: '.implode(', ', $unknown).'.');
                }
            },
        ];
    }
}
