// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/form22.c
extern int unknown_int(void);

void loopy_93(int x2, int x3, int x1p, int x2p, int x3p, int input)
{
  int x1;
  

  x1 = x2 = x3 = 0;
  while(input)
  {
    x1p = unknown_int();
    x2p = unknown_int();
    x3p = unknown_int();

    if (x1p <= x2p && (x2p >= 0 || x2p - x3p <= 2))
    {
	x1 = x1p;
	x2 = x2p;
	x3 = x3p;
    }
    input = unknown_int();
  }
  {;
//@ assert(x1 <= x2 && (x2 >= 0 || x2 - x3 <= 2));
}
    
}
