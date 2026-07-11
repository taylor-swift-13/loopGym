// Source: data/benchmarks/LinearArbitrary-SeaHorn/invgen/simple.c
extern int unknown(void);

/*@
  requires n > 0;
*/
void loopy_39(int n) {
  int x=0;
  
  
  
  while( x < n ){
    x++;
  }
  {;
//@ assert( x<=n );
}

}