// Source: data/benchmarks/LinearArbitrary-SeaHorn/pie/hola/08.c

extern int unknown1();
extern int unknown2();
extern int unknown3();

void loopy_122(void) {
 int x = 0, y = 0;
 while(unknown1()){
   if(unknown2()){ 
      x++; 
      y+=100; 
   }
   else if (unknown3()){ 
      if (x >= 4) { 
          x++; 
          y++; 
      } 
      if (x < 0){
          y = -y;
      }
   }
  
 }
 {;
//@ assert(x < 4 || y > 2);
}

}