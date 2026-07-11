// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/ICE/benchmarks/incn.c
extern int unknown_int(void);

/*@
  requires !(N < 0);
*/
void loopy_97(int N)
{
  int x;
  x = 0;
  

  while(x < N)
  {
    x = x + 1;
  }
  {;
//@ assert(x == N);
}
    
return;

}
