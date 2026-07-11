// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/incn.v.c
extern int unknown_int(void);

void loopy_98(int N, int v1, int v2, int v3)
{
  int x;
  x = 0;
  while(x < N)
  {
    x = x + 1;
    v1 = unknown_int();
    v2 = unknown_int();
    v3 = unknown_int();
  }
  {;
//@ assert(N < 0 || x == N);
}
    
}
