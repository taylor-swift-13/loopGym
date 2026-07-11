// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/dec.c
extern int unknown_int(void);

void loopy_84(int m)
{
  int x;
  x = 100;
  while(x > 0)
  {
    m = unknown_int();
    x = x - 1;
  }
  {;
//@ assert(x == 0);
}
    
}
