// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/gulwani_fig1a.c
extern int unknown(void);

extern int unknown();

void loopy_33(int y) {
  int x;
  x = -50;
  while( x < 0 ) {
	x = x+y;
	y++;
  }
  {;
//@ assert(y>0);
}

}