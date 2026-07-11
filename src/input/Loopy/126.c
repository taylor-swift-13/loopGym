// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/14.c

extern int unknown1();

/*@
  requires !(m<=0);
*/
void loopy_126(int j, int m) {
  int a = 0;
  
  
  
  {
  j = 1;
  while (j <= m) {
    if(unknown1()) 
           a++;
        else
           a--;
    j++;
  }
}
  {;
//@ assert(a>=-m && a<=m);
}

}