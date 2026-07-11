// Source: data/benchmarks/accelerating_invariant_generation/dagger/ex1.c
extern int unknown_int(void);

int nondet_int();

void loopy_179(int x, int y) {



int xa = 0;
int ya = 0;

while (unknown_int()) {
	x = xa + 2*ya;
	y = -2*xa + ya;

	x++;
	if (unknown_int()) y	= y+x;
	else y = y-x;

	xa = x - 2*y;
	ya = 2*x + y;
}

{;
//@ assert(xa + 2*ya >= 0);
}

return;
}
