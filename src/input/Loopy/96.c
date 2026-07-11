// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/inc.c
extern int unknown_int(void);

void loopy_96(int m)
{
  int x;
  x = 0;
  while(x < 100)
  {
    m = unknown_int();
    x = x + 1;
  }
  {;
//@ assert(x == 100);
}
    
}
