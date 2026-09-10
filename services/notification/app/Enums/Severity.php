<?php

namespace App\Enums;

enum Severity: string
{
    case C = 'C';
    case B = 'B';
    case A = 'A';
    case S = 'S';

    public function rank(): int
    {
        return match ($this) {
            self::C => 0,
            self::B => 1,
            self::A => 2,
            self::S => 3,
        };
    }
}
