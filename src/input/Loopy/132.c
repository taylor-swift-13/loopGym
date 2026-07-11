// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/21.c

extern int unknown1();
extern int unknown2();

/*@
  requires n > 0 && n < 10;
*/
void loopy_132(int n, int v, int j) {
  int c1 = 4000;
  int c2 = 2000;
  
  int i, k;

  

  k = 0;
  i = 0;
  while( i < n ) {
    i++;
    if(unknown2() % 2 == 0) 
      v = 0;
    else v = 1;
    
    if( v == 0 )
      k += c1;
    else 
      k += c2;
  }
  
  {;
//@ assert(k>n);
}

  return;
}
