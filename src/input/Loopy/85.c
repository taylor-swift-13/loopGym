// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/decn.c
extern int unknown_int(void);

/*@
  requires !(N < 0);
*/
void loopy_85(int m, int N)
{
  int x;
  

  x = N;
  while(x > 0)
  {
    x = x - 1;
  }
  {;
//@ assert(x == 0);
}
    
}
